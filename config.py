"""配置管理 —— 用户设置持久化（JSON 文件）。"""

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "storage" / "settings.json"

DEFAULT_CONFIG = {
    # 监听设置
    "monitor": {
        "enabled": True,
        "window_poll_interval": 0.5,       # 窗口轮询间隔（秒）
        "idle_timeout": 30.0,              # 空闲超时（秒）
        "flush_interval": 5.0,             # 批量写入间隔（秒）
        "capture_keyboard": True,
        "capture_mouse_clicks": True,
        "capture_mouse_moves": False,      # 鼠标移动默认不录（省资源）
    },
    # 分析设置
    "analyzer": {
        "auto_analyze": True,
        "min_occurrences": 3,              # 最少出现次数才算习惯
        "analysis_hours": [12, 18],        # 自动分析时间
        "lookback_days": 7,                # 扫描历史天数
    },
    # 执行设置
    "executor": {
        "confirm_delay": 3,                # 执行前倒计时（秒）
        "max_actions_per_habit": 50,       # 单习惯最大动作数
        "enable_auto_execute": False,      # 全局自动执行开关
    },
    # 精灵外观
    "spirit": {
        "skin": "default",
        "opacity": 0.85,
        "size": 140,
        "auto_hide": False,
        "always_on_top": True,
    },
    # 窗口
    "window": {
        "width": 960,
        "height": 680,
        "save_position": True,
    },
    # 隐私
    "privacy": {
        "record_keys": True,               # 是否记录具体按键
        "record_window_titles": True,      # 是否记录窗口标题
        "retention_days": 30,              # 数据保留天数
    },
}


class Settings:
    """线程安全的配置管理器。"""

    def __init__(self):
        self._data = DEFAULT_CONFIG.copy()
        self._loaded = False

    # ── 持久化 ──────────────────────────────────

    def load(self):
        """从 JSON 文件加载配置。"""
        if self._loaded:
            return
        self._loaded = True
        if not CONFIG_FILE.exists():
            self.save()
            return
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            # 合并（保留默认值中缺失的键）
            self._deep_merge(self._data, loaded)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[配置] 加载失败，使用默认值: {e}")

    def save(self):
        """保存配置到 JSON 文件。"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[配置] 保存失败: {e}")

    # ── 读写 ────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        """用点分路径读取配置项。e.g. get('monitor.enabled')"""
        keys = key.split(".")
        val = self._data
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key: str, value: Any):
        """用点分路径写入配置项。"""
        keys = key.split(".")
        target = self._data
        for k in keys[:-1]:
            target = target.setdefault(k, {})
        target[keys[-1]] = value
        self.save()

    def get_all(self) -> dict:
        return self._data

    # ── 合并 ────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict, override: dict):
        """递归合并字典（保留 base 中 override 没有的键）。"""
        for k, v in override.items():
            if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                Settings._deep_merge(base[k], v)
            else:
                base[k] = v


# 全局单例
settings = Settings()
settings.load()
