"""V2 活动监控 —— 更健壮的窗口/输入监听。"""

import threading
import time
import logging
from datetime import datetime
from typing import Callable, Optional

import win32gui
import win32process
import win32api

logger = logging.getLogger(__name__)


def get_foreground_window() -> dict:
    """获取前台窗口信息，返回 {title, exe, hwnd}。"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = win32gui.GetWindowText(hwnd).strip() or "(无标题)"
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        handle = win32api.OpenProcess(0x0400 | 0x0010, False, pid)
        exe = ""
        if handle:
            try:
                exe = win32process.GetModuleFileNameEx(handle, 0).split("\\")[-1]
            except Exception:
                pass
            win32api.CloseHandle(handle)
        return {"title": title, "exe": exe, "hwnd": hwnd, "pid": pid}
    except Exception as e:
        logger.debug(f"获取窗口信息失败: {e}")
        return {"title": "(未知)", "exe": "", "hwnd": 0, "pid": 0}


class WindowMonitor:
    """窗口切换监听器（轮询模式）。"""

    def __init__(self, on_change: Callable, interval: float = 0.5):
        self._on_change = on_change
        self._interval = interval
        self._last = ""
        self._last_exe = ""
        self._last_time = 0.0
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        t = threading.Thread(target=self._poll, daemon=True, name="win-mon")
        t.start()

    def stop(self):
        self._running = False

    def _poll(self):
        while self._running:
            try:
                info = get_foreground_window()
                title = info["title"]
                now = time.time()
                if title != self._last and (now - self._last_time) > 1.0:
                    old = self._last
                    self._last = title
                    self._last_exe = info["exe"]
                    self._last_time = now
                    if old:
                        self._on_change("window_focus", {
                            "from": old, "to": title,
                            "exe": info["exe"],
                        }, title)
            except Exception:
                logger.debug("窗口轮询异常", exc_info=True)
            time.sleep(self._interval)


class InputMonitor:
    """鼠标/键盘输入监听器（基于 pynput）。"""

    def __init__(self, on_event: Callable, capture_keys: bool = True,
                 capture_clicks: bool = True):
        self._on_event = on_event
        self._capture_keys = capture_keys
        self._capture_clicks = capture_clicks
        self._mouse_listener = None
        self._key_listener = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            from pynput import mouse, keyboard
            if self._capture_clicks:
                self._mouse_listener = mouse.Listener(
                    on_click=self._on_click,
                    on_scroll=self._on_scroll
                )
                self._mouse_listener.daemon = True
                self._mouse_listener.start()
            if self._capture_keys:
                self._key_listener = keyboard.Listener(on_press=self._on_key)
                self._key_listener.daemon = True
                self._key_listener.start()
        except Exception as e:
            logger.error(f"输入监听启动失败: {e}")

    def stop(self):
        self._running = False
        try:
            if self._mouse_listener:
                self._mouse_listener.stop()
            if self._key_listener:
                self._key_listener.stop()
        except Exception:
            pass

    def _get_window(self) -> str:
        return get_foreground_window()["title"]

    def _on_click(self, x, y, button, pressed):
        if not self._running:
            return False
        if pressed:
            self._on_event("click", {
                "x": x, "y": y, "button": str(button)
            }, self._get_window())
        return self._running

    def _on_scroll(self, x, y, dx, dy):
        if not self._running:
            return False
        self._on_event("scroll", {"x": x, "y": y, "dx": dx, "dy": dy},
                       self._get_window())
        return self._running

    def _on_key(self, key):
        if not self._running:
            return False
        try:
            k = key.char if hasattr(key, 'char') and key.char else str(key)
        except Exception:
            k = str(key)
        self._on_event("keypress", {"key": k}, self._get_window())
        return self._running


class ActivityMonitor:
    """整合窗口 + 输入监听。"""

    def __init__(self, on_event: Callable):
        self._on_event = on_event
        self._win_mon = WindowMonitor(on_event)
        self._inp_mon = InputMonitor(on_event)

    def start(self):
        self._win_mon.start()
        self._inp_mon.start()
        logger.info("✅ 监控已启动")

    def stop(self):
        self._win_mon.stop()
        self._inp_mon.stop()
        logger.info("⏹ 监控已停止")

    @property
    def running(self):
        return self._win_mon._running
