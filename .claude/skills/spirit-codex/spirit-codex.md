---
name: spirit-codex
description: 管理与分析桌面精灵的进化、错误修复和升级
model: opus
---

# 🧠 桌面精灵 Codex 管理技能

作为桌面精灵的"大脑"，你负责分析精灵的运行数据、修复错误、规划升级。

## 使用流程

```bash
# 查看精灵状态
python core/codex_integration.py status

# 分析错误报告
python core/codex_integration.py analyze-errors

# 响应精灵的升级请求
python core/codex_integration.py respond
```

## 数据文件位置

所有精灵数据在 `storage/codex/` 下：

| 文件 | 说明 |
|------|------|
| `errors/` | 精灵自动提交的错误报告（Markdown） |
| `evolution.json` | 精灵进化轨迹（JSON） |
| `upgrade_request.md` | 精灵请求的新功能 |
| `codex_response.md` | **你的回复文件**——写此文件让精灵读取执行 |
| `reports/` | 精灵的分析报告 |

## 工作流

### 1️⃣ 定期检查

每次被调用时：
1. 读取 `evolution.json` —— 了解精灵成长状态
2. 检查 `errors/` 目录 —— 是否有待处理的错误
3. 读取 `upgrade_request.md` —— 精灵想要什么新能力

### 2️⃣ 处理错误

当精灵报告错误时：
1. 读取 `errors/_latest.md` 获取最新错误详情
2. 分析错误原因（代码问题 / 环境问题 / 使用问题）
3. 修复源码并提交 PR
4. 在 `codex_response.md` 中回复处理结果

### 3️⃣ 规划升级

当精灵请求升级时：
1. 读取 `upgrade_request.md` 了解需求
2. 分析可行性和优先级
3. 实施新功能（修改代码）
4. 更新 `evolution.json` 的版本号
5. 在 `codex_response.md` 中告知精灵升级完成

### 4️⃣ 回复格式

`codex_response.md` 使用以下格式让精灵读取执行：

```json
{
  "action": "set_config",
  "params": {
    "key": "analyzer.min_occurrences",
    "value": 2
  }
}
```

支持的 action:
- `set_config` — 修改精灵配置
- `apply_patch` — 提供代码补丁
- `request_data` — 让精灵生成更多数据
- `log` — 给精灵发送一条消息
- `upgrade_habit` — 修改某个习惯的参数
