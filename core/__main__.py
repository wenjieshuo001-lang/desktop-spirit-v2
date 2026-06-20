"""Codex CLI 入口 —— 从命令行管理桌面精灵。"""

import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from core import codex_integration as cx
from core import database as db


def main():
    if len(sys.argv) < 2:
        _print_help()
        return

    command = sys.argv[1]

    if command == "status":
        _cmd_status()
    elif command == "analyze-errors":
        _cmd_errors()
    elif command == "report":
        _cmd_report()
    elif command == "respond":
        _cmd_respond()
    elif command == "upgrade":
        _cmd_upgrade()
    elif command == "request":
        _cmd_request()
    elif command == "evolution":
        print(cx.get_evolution_summary())
    else:
        print(f"未知命令: {command}")
        _print_help()


def _print_help():
    print("""
🧠 桌面精灵 Codex 管理工具

用法:
  python core/ status             查看精灵状态
  python core/ analyze-errors     分析待处理的错误
  python core/ report             生成完整分析报告
  python core/ respond            回复精灵的升级请求
  python core/ upgrade            执行 Codex 响应中的指令
  python core/ evolution          查看进化轨迹
""")


def _cmd_status():
    habits = db.get_habits(active_only=True)
    stats = db.get_daily_stats(1)

    print(f"""
🧠 桌面精灵状态
═══════════════════════════════════
活跃习惯: {len(habits)} 个
""")

    # 错误状态
    error_files = []
    if os.path.exists(cx.ERRORS_DIR):
        error_files = [f for f in os.listdir(cx.ERRORS_DIR) if f.endswith(".md") and f != "_latest.md"]
    print(f"待处理错误: {len(error_files)} 个")

    # 升级请求
    if os.path.exists(cx.UPGRADE_REQUEST):
        with open(cx.UPGRADE_REQUEST, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            lines = content.split("\n")
            print(f"升级请求: {len([l for l in lines if l.startswith('## ')])} 条")

    # 进化
    if os.path.exists(cx.EVOLUTION_FILE):
        with open(cx.EVOLUTION_FILE, "r", encoding="utf-8") as f:
            ev = json.load(f)
        print(f"""
版本: {ev.get('version', '-')}
总分析: {ev.get('total_analyses', 0)} 次
总执行: {ev.get('total_executions', 0)} 次
里程碑: {len(ev.get('milestones', []))} 个
""")

    print("═══════════════════════════════════")
    print("\n运行 python core/ report 查看完整报告")


def _cmd_errors():
    error_files = []
    if os.path.exists(cx.ERRORS_DIR):
        error_files = sorted([
            f for f in os.listdir(cx.ERRORS_DIR)
            if f.endswith(".md") and f != "_latest.md"
        ])

    if not error_files:
        print("✅ 没有待处理的错误报告")
        return

    print(f"📋 发现 {len(error_files)} 个待处理错误:\n")
    for f in error_files[-10:]:
        filepath = os.path.join(cx.ERRORS_DIR, f)
        with open(filepath, "r", encoding="utf-8") as fp:
            content = fp.read()
        # 只显示前几行
        lines = content.split("\n")
        print(f"  📄 {f}")
        for line in lines[1:6]:
            if line.strip():
                print(f"    {line.strip()}")
        print()


def _cmd_report():
    report = cx.generate_analytics_report()
    print(f"✅ 分析报告已生成")
    print()
    # 显示摘要
    for line in report.split("\n")[:20]:
        print(line)


def _cmd_respond():
    response = cx.read_codex_response()
    if not response:
        print("📭 没有待处理的 Codex 响应")
        return

    print(f"📩 收到 Codex 响应:")
    print(f"  指令: {len(response['commands'])} 条")
    print(f"  补丁: {len(response['patches'])} 个")
    print()

    for cmd in response["commands"]:
        action = cmd.get("action", "?")
        params = cmd.get("params", {})
        print(f"  ⚡ {action}: {json.dumps(params, ensure_ascii=False)[:80]}")

    # 执行指令
    confirm = input("\n是否执行这些指令？(y/N): ")
    if confirm.lower() == "y":
        for cmd in response["commands"]:
            cx._execute_codex_command(cmd)
        print("✅ 指令已执行")


def _cmd_upgrade():
    """处理精灵的升级请求。"""
    if not os.path.exists(cx.UPGRADE_REQUEST):
        print("📭 没有升级请求")
        return

    with open(cx.UPGRADE_REQUEST, "r", encoding="utf-8") as f:
        content = f.read()

    print(content)

    action = input("\n是否清空已处理的请求？(y/N): ")
    if action.lower() == "y":
        open(cx.UPGRADE_REQUEST, "w", encoding="utf-8").close()
        print("✅ 升级请求已清空")


def _cmd_request():
    """精灵请求新功能。"""
    if len(sys.argv) < 3:
        print("用法: python core/ request <标题> [描述]")
        return
    title = sys.argv[2]
    desc = " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "请 Codex 分析并实现"
    prio = input("优先级 (high/medium/low) [medium]: ").strip() or "medium"
    cx.request_upgrade(title, desc, prio)
    print(f"✅ 升级请求已提交: {title}")


if __name__ == "__main__":
    main()
