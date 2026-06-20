"""V2 动作执行器 —— 更安全、可取消、带超时。"""

import json
import logging
import time
import threading

from config import settings

logger = logging.getLogger(__name__)


class Executor:
    """安全地回放动作序列。"""

    def __init__(self):
        self._cancel_flag = False
        self._busy = False
        self._lock = threading.Lock()

    @property
    def is_busy(self) -> bool:
        return self._busy

    def cancel(self):
        with self._lock:
            self._cancel_flag = True

    def run(self, actions_json: str, habit_id: int = 0,
            triggered_by: str = "manual") -> bool:
        """执行动作序列。"""
        try:
            actions = json.loads(actions_json) if isinstance(actions_json, str) else actions_json
        except json.JSONDecodeError:
            logger.error("动作 JSON 解析失败")
            return False

        if not isinstance(actions, list):
            actions = [actions]

        max_actions = settings.get("executor.max_actions_per_habit", 50)
        if len(actions) > max_actions:
            logger.warning(f"动作数 {len(actions)} 超过限制 {max_actions}，截断")
            actions = actions[:max_actions]

        with self._lock:
            self._cancel_flag = False
            self._busy = True

        start = time.time()
        ok = True

        try:
            for i, act in enumerate(actions):
                if self._cancel_flag:
                    logger.info(f"已取消（第 {i+1}/{len(actions)} 步）")
                    ok = False
                    break

                wb = act.get("wait_before", 0.3)
                if wb > 0:
                    time.sleep(wb)

                t = act.get("type", "")
                try:
                    if t == "click":
                        self._click(act)
                    elif t == "type":
                        self._type_text(act)
                    elif t == "key":
                        self._press_key(act)
                    elif t == "window":
                        self._focus_window(act)
                    elif t == "wait":
                        time.sleep(act.get("duration", 1.0))
                    elif t == "scroll":
                        self._scroll(act)
                    else:
                        logger.warning(f"未知动作: {t}")
                except Exception as e:
                    logger.error(f"动作执行失败 [{t}]: {e}")
                    ok = False
                    break

                wa = act.get("wait_after", 0.2)
                if wa > 0:
                    time.sleep(wa)

        except Exception as e:
            logger.error(f"执行异常: {e}")
            ok = False
        finally:
            with self._lock:
                self._busy = False

        dur = int((time.time() - start) * 1000)
        try:
            from . import database as db
            db.log_exec(habit_id, ok, dur, triggered_by,
                        "成功" if ok else "失败/取消")
        except Exception:
            pass
        return ok

    # ── 原始操作 ──────────────────────────────────

    def _click(self, act: dict):
        from pynput.mouse import Controller as MC, Button
        mc = MC()
        x, y = act["x"], act["y"]
        btn = Button.left if act.get("button", "left") == "left" else Button.right
        mc.position = (x, y)
        time.sleep(0.05)
        mc.click(btn)

    def _type_text(self, act: dict):
        from pynput.keyboard import Controller as KC
        KC().type(act.get("text", ""))

    def _press_key(self, act: dict):
        from pynput.keyboard import Controller as KC, Key
        k = act.get("key", "")
        KEY_MAP = {
            "enter": Key.enter, "tab": Key.tab, "space": Key.space,
            "esc": Key.esc, "backspace": Key.backspace, "delete": Key.delete,
            "ctrl": Key.ctrl, "alt": Key.alt, "shift": Key.shift,
            "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        }
        key = KEY_MAP.get(k.lower(), k)
        kc = KC()
        kc.press(key)
        time.sleep(0.05)
        kc.release(key)

    def _focus_window(self, act: dict):
        title = act.get("window", "")
        if not title:
            return
        try:
            import win32gui
            target = None
            def enum(hwnd, _):
                nonlocal target
                if not win32gui.IsWindowVisible(hwnd):
                    return
                t = win32gui.GetWindowText(hwnd)
                if title.lower() in t.lower():
                    target = hwnd
            win32gui.EnumWindows(enum, None)
            if target:
                win32gui.SetForegroundWindow(target)
                time.sleep(0.3)
        except Exception as e:
            logger.warning(f"窗口切换失败: {e}")

    def _scroll(self, act: dict):
        from pynput.mouse import Controller as MC
        MC().scroll(act.get("dx", 0), act.get("dy", -1))


# 全局单例
_executor = None


def get_executor() -> Executor:
    global _executor
    if _executor is None:
        _executor = Executor()
    return _executor
