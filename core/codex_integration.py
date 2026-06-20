"""Codex 桥接模块 —— 桌面精灵的进化 / 报错 / 升级 全部交给 Codex 处理。

工作流：
1. 精灵收集数据 → 写入 storage/codex/ 结构化文件
2. Codex (Claude Code) 读取这些文件 → 分析 / 修复 / 升级
3. Codex 写入响应文件 → 精灵读取并执行

文件协议 (storage/codex/)：
  errors/      ─ 错误报告（精灵遇到异常时写入）
  evolution.json ─ 精灵进化轨迹（版本 / 习惯数 / 能力）
  upgrade_request.md ─ 升级请求（精灵向 Codex 请求新功能）
  codex_response.md  ─ Codex 的响应（精灵读取执行）
"""

import json
import os
import logging
import shutil
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

CODEX_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage", "codex")
ERRORS_DIR = os.path.join(CODEX_DIR, "errors")
REPORTS_DIR = os.path.join(CODEX_DIR, "reports")
EVOLUTION_FILE = os.path.join(CODEX_DIR, "evolution.json")
UPGRADE_REQUEST = os.path.join(CODEX_DIR, "upgrade_request.md")
CODEX_RESPONSE = os.path.join(CODEX_DIR, "codex_response.md")


# ═══════════════════════════════════════════════
# 1. 错误报告 —— 精灵遇到异常时提交给 Codex
# ═══════════════════════════════════════════════

def report_error(component: str, error: Exception, context: dict = None):
    """将运行时错误报告给 Codex。"""
    os.makedirs(ERRORS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{component}.md"
    filepath = os.path.join(ERRORS_DIR, filename)

    content = f"""# 🐛 错误报告

**时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**组件**: {component}
**版本**: 2.0-beta

## 错误信息

```
{error.__class__.__name__}: {error}
```

## 上下文

```json
{json.dumps(context or {}, indent=2, ensure_ascii=False)}
```

## 调用栈

```
{_format_traceback(error)}
```

## 请 Codex 处理

1. 分析此错误的根本原因
2. 给出修复方案（代码 diff）
3. 如果需要，自动修改源码修复

---
*此报告由桌面精灵自动生成*
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    # 同时写入最新的错误（方便 Codex 快速读取）
    latest = os.path.join(ERRORS_DIR, "_latest.md")
    shutil.copy(filepath, latest)

    logger.info(f"📮 错误已报告给 Codex: {filename}")
    return filepath


def _format_traceback(error: Exception) -> str:
    import traceback
    return "".join(traceback.format_exception(type(error), error, error.__traceback__))


# ═══════════════════════════════════════════════
# 2. 进化追踪 —— 精灵的成长轨迹
# ═══════════════════════════════════════════════

def update_evolution(metrics: dict):
    """更新精灵的进化数据。"""
    os.makedirs(CODEX_DIR, exist_ok=True)
    data = {}
    if os.path.exists(EVOLUTION_FILE):
        try:
            with open(EVOLUTION_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            data = {}

    # 初始化进化记录
    if "first_seen" not in data:
        data["first_seen"] = datetime.now().isoformat()
    data["last_updated"] = datetime.now().isoformat()

    # 版本信息
    data.setdefault("version", "2.0-beta")

    # 习惯数量历史
    history = data.setdefault("habit_history", [])
    if metrics.get("habit_count") is not None:
        today = datetime.now().strftime("%Y-%m-%d")
        if not history or history[-1]["date"] != today:
            history.append({
                "date": today,
                "count": metrics["habit_count"],
                "source": metrics.get("analysis_source", "auto"),
            })
            # 只保留最近 90 天
            if len(history) > 90:
                history[:] = history[-90:]

    # 累计统计
    data.setdefault("total_analyses", 0)
    data.setdefault("total_executions", 0)
    data.setdefault("total_errors", 0)

    if metrics.get("analysis_ran"):
        data["total_analyses"] += 1
    if metrics.get("execution_count"):
        data["total_executions"] += metrics["execution_count"]
    if metrics.get("error_count"):
        data["total_errors"] += metrics["error_count"]

    # 里程碑检测
    milestones = data.setdefault("milestones", [])
    _check_milestone(milestones, "first_habit", metrics.get("habit_count", 0) >= 1,
                     "🎯 学习了第 1 个习惯")
    _check_milestone(milestones, "ten_habits", metrics.get("habit_count", 0) >= 10,
                     "🌟 学会了 10 个习惯")
    _check_milestone(milestones, "fifty_habits", metrics.get("habit_count", 0) >= 50,
                     "🏆 学会了 50 个习惯")
    _check_milestone(milestones, "first_execution", metrics.get("execution_count", 0) >= 1,
                     "⚡ 首次自动执行")
    _check_milestone(milestones, "hundred_executions", metrics.get("execution_count", 0) >= 100,
                     "🎯 累计执行 100 次")

    with open(EVOLUTION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _check_milestone(milestones: list, key: str, condition: bool, message: str):
    if condition and not any(m["key"] == key for m in milestones):
        milestones.append({
            "key": key,
            "message": message,
            "achieved_at": datetime.now().isoformat(),
        })


def get_evolution_summary() -> str:
    """生成进化摘要 Markdown（给 Codex 看）。"""
    if not os.path.exists(EVOLUTION_FILE):
        return "精灵还没有进化数据。"

    try:
        with open(EVOLUTION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return "进化数据损坏。"

    lines = [
        "## 🧬 桌面精灵进化报告",
        "",
        f"**版本**: {data.get('version', '未知')}",
        f"**首次启动**: {data.get('first_seen', '未知')}",
        f"**最近更新**: {data.get('last_updated', '未知')}",
        "",
        "### 📊 统计",
        f"- 总分析次数: {data.get('total_analyses', 0)}",
        f"- 总执行次数: {data.get('total_executions', 0)}",
        f"- 总错误数: {data.get('total_errors', 0)}",
        "",
    ]

    history = data.get("habit_history", [])
    if history:
        lines.append("### 📈 习惯数量变化")
        lines.append("")
        lines.append("| 日期 | 数量 | 来源 |")
        lines.append("|------|------|------|")
        for h in history[-14:]:  # 近两周
            lines.append(f"| {h['date']} | {h['count']} | {h.get('source', '-')} |")
        lines.append("")

    milestones = data.get("milestones", [])
    if milestones:
        lines.append("### 🏅 里程碑")
        lines.append("")
        for m in milestones:
            lines.append(f"- {m['message']} ({m['achieved_at']})")
        lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════
# 3. 升级请求 —— 精灵向 Codex 请求新功能 / 改进
# ═══════════════════════════════════════════════

def request_upgrade(title: str, description: str, priority: str = "medium",
                    suggestions: str = None):
    """精灵向 Codex 提交升级请求。"""
    os.makedirs(CODEX_DIR, exist_ok=True)

    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    icon = priority_icon.get(priority, "🟡")

    # 读取已有的升级请求
    existing = ""
    if os.path.exists(UPGRADE_REQUEST):
        with open(UPGRADE_REQUEST, "r", encoding="utf-8") as f:
            existing = f.read()

    new_entry = f"""
## {icon} [{priority.upper()}] {title}

**请求时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{description}

"""
    if suggestions:
        new_entry += f"**建议方向**: {suggestions}\n\n"
    new_entry += "---\n"

    with open(UPGRADE_REQUEST, "w", encoding="utf-8") as f:
        f.write(new_entry + existing)

    logger.info(f"📮 升级请求已提交: [{priority}] {title}")


# ═══════════════════════════════════════════════
# 4. 分析报告 —— 将精灵数据导出为 Codex 可读的 Markdown
# ═══════════════════════════════════════════════

def generate_analytics_report() -> str:
    """生成完整的分析报告（Markdown）。"""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    from . import database as db

    habits = db.get_habits(active_only=True)
    stats = db.get_daily_stats(7)

    lines = [
        "# 📊 桌面精灵分析报告",
        "",
        f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**活跃习惯数**: {len(habits)}",
        "",
        "## 📋 当前习惯列表",
        "",
    ]

    for h in habits:
        conf = float(h.get("confidence", 0))
        bar = "█" * int(conf * 10) + "░" * (10 - int(conf * 10))
        lines.append(f"- **{h['name']}** [{bar} {conf:.0%}]")
        lines.append(f"  - 类型: {h['pattern_type']} | 频率: {h['frequency']} | {h.get('typical_time', '')}")
        lines.append(f"  - {h.get('desc', '')}")
        lines.append("")

    if stats:
        lines.append("## 📈 近 7 日活动趋势")
        lines.append("")
        lines.append("| 日期 | 点击 | 按键 | 新习惯 |")
        lines.append("|------|------|------|--------|")
        for s in stats:
            lines.append(f"| {s['date']} | {s['clicks']} | {s['keys']} | {s['habits_new']} |")
        lines.append("")

    # 列出未处理的错误
    error_files = sorted(os.listdir(ERRORS_DIR)) if os.path.exists(ERRORS_DIR) else []
    pending_errors = [f for f in error_files if f != "_latest.md"]
    if pending_errors:
        lines.append(f"## 🐛 待处理错误 ({len(pending_errors)})")
        lines.append("")
        for f in pending_errors[-10:]:
            lines.append(f"- [{f}](errors/{f})")
        lines.append("")

    # 升级请求
    if os.path.exists(UPGRADE_REQUEST):
        with open(UPGRADE_REQUEST, "r", encoding="utf-8") as f:
            content = f.read()
        if content.strip():
            lines.append("## ⬆️ 待处理的升级请求")
            lines.append("")
            lines.append(content)

    report = "\n".join(lines)

    # 保存报告
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(REPORTS_DIR, f"report_{timestamp}.md")
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(report)

    return report


# ═══════════════════════════════════════════════
# 5. Codex 响应读取 —— 精灵读取 Codex 的回复
# ═══════════════════════════════════════════════

def read_codex_response() -> Optional[dict]:
    """读取 Codex 的响应并解析为结构化指令。"""
    if not os.path.exists(CODEX_RESPONSE):
        return None

    try:
        with open(CODEX_RESPONSE, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError:
        return None

    # 解析 Markdown 中的 JSON 指令块
    result = {"raw": content, "commands": [], "patches": []}

    import re
    # 查找 ```json ... ``` 块
    for match in re.finditer(r"```json\n(.+?)\n```", content, re.DOTALL):
        try:
            cmd = json.loads(match.group(1))
            result["commands"].append(cmd)
        except json.JSONDecodeError:
            pass

    # 查找 ```patch ... ``` 块（代码补丁）
    for match in re.finditer(r"```patch\n(.+?)\n```", content, re.DOTALL):
        result["patches"].append(match.group(1))

    return result


# ═══════════════════════════════════════════════
# 6. 整合入口 —— 精灵定期调用
# ═══════════════════════════════════════════════

# ── 可安全自动执行的指令（只读） ───────────────
_SAFE_ACTIONS = {"log", "request_data"}

# ── 配置白名单 —— set_config 只能修改这些键 ────
_CONFIG_WHITELIST = {
    "spirit.skin",
    "spirit.opacity",
    "spirit.size",
    "spirit.auto_hide",
    "spirit.always_on_top",
    "analyzer.min_occurrences",
    "analyzer.lookback_days",
    "executor.confirm_delay",
}


def sync_with_codex(habit_count: int = 0, analysis_ran: bool = False,
                    execution_count: int = 0, error_count: int = 0):
    """统一向 Codex 同步精灵的最新状态。

    ⚠️ 仅自动执行只读指令（log, request_data），
       修改性指令（apply_patch, set_config）需用户确认。
    """
    # 更新进化数据
    update_evolution({
        "habit_count": habit_count,
        "analysis_ran": analysis_ran,
        "execution_count": execution_count,
        "error_count": error_count,
    })

    # 检查 Codex 是否有新指令
    response = read_codex_response()
    if response and response["commands"]:
        safe_cmds = []
        dangerous_cmds = []
        for cmd in response["commands"]:
            if cmd.get("action") in _SAFE_ACTIONS:
                safe_cmds.append(cmd)
            else:
                dangerous_cmds.append(cmd)

        # 自动执行安全指令
        for cmd in safe_cmds:
            _execute_codex_command(cmd)

        # 危险指令排队等待用户确认
        if dangerous_cmds:
            _queue_dangerous_commands(dangerous_cmds)
            logger.info(f"📨 {len(dangerous_cmds)} 条修改性指令等待用户确认")
    else:
        logger.debug("没有新的 Codex 指令")

    return response


def _queue_dangerous_commands(commands: list):
    """将修改性指令写入队列文件，等待用户确认。"""
    os.makedirs(CODEX_DIR, exist_ok=True)
    queue_file = os.path.join(CODEX_DIR, "pending_commands.json")

    existing = []
    if os.path.exists(queue_file):
        try:
            with open(queue_file, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    existing.extend(commands)
    with open(queue_file, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)


def _execute_codex_command(cmd: dict):
    """执行 Codex 下发的指令。"""
    action = cmd.get("action", "")
    params = cmd.get("params", {})

    logger.info(f"⚡ 执行 Codex 指令: {action}")

    if action == "upgrade_habit":
        # Codex 要求升级某个习惯
        from . import database as db
        hid = params.get("habit_id")
        if hid:
            h = db.get_habit(hid)
            if h:
                db._update_habit(hid,
                                 name=params.get("name", h["name"]),
                                 desc=params.get("desc", h["desc"]),
                                 confidence=params.get("confidence", h["confidence"]))

    elif action == "apply_patch":
        # Codex 提供了代码补丁
        patch_content = params.get("content", "")
        target_file = params.get("file", "")
        if patch_content and target_file:
            _apply_patch(target_file, patch_content)

    elif action == "request_data":
        # Codex 请求更多数据（只读，安全）
        return generate_analytics_report()

    elif action == "set_config":
        # Codex 修改配置（受白名单限制）
        key = params.get("key", "")
        value = params.get("value")

        # 校验白名单
        if key not in _CONFIG_WHITELIST:
            logger.warning(f"配置键被白名单拒绝: {key}")
            return

        # 校验值类型
        if key.endswith(".opacity") and not (0 <= float(value) <= 1):
            logger.warning(f"配置值不合法: {key}={value}")
            return

        from config import settings
        settings.set(key, value)
        logger.info(f"⚙️ 配置已更新: {key} = {value}")

    elif action == "log":
        logger.info(f"[Codex] {params.get('message', '')}")

    else:
        logger.warning(f"未知 Codex 指令: {action}")


def _apply_patch(filepath: str, content: str):
    """应用补丁到源码文件（安全：校验路径不越界）。"""
    # 解析并校验路径 —— 防止 Path Traversal
    project_root = os.path.realpath(os.path.dirname(os.path.dirname(__file__)))
    full_path = os.path.realpath(os.path.join(project_root, filepath))

    if not full_path.startswith(project_root + os.sep):
        logger.error(f"路径越界被拒绝: {filepath} → {full_path}")
        return

    if not os.path.exists(full_path):
        logger.error(f"补丁目标不存在: {full_path}")
        return

    try:
        # 备份原文件
        backup = full_path + ".bak"
        shutil.copy2(full_path, backup)

        # 应用补丁（简单的全文替换模式）
        with open(full_path, "r", encoding="utf-8") as f:
            original = f.read()

        # 如果补丁被标记为 diff，暂不处理复杂 diff
        if content.startswith("---"):
            logger.warning("diff 格式补丁暂不支持，跳过")
            return
        else:
            # 直接替换文件
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

        logger.info(f"📝 补丁已应用到: {filepath}")
    except Exception as e:
        logger.error(f"补丁应用失败: {e}")
