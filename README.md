# 🧠 桌面精灵 V2 测试版

学习你的工作习惯，自动执行重复操作。

## V2 改进

| 改进项 | V1 | V2 |
|--------|----|----|
| paintEvent Bug | ❌ QRect → QPainterPath 崩溃 | ✅ QRectF 修复 |
| 配置系统 | ❌ 无 | ✅ config.py JSON 管理 |
| 精灵动画 | 静态 | ✅ 30fps 呼吸 + 渐变 + 高光 |
| 分析策略 | 3 种 | ✅ 4 种（+ 活跃时段） |
| 搜索/筛选 | ❌ 无 | ✅ 搜索 + 分类 + 自动筛选 |
| 导出/导入 | ❌ 无 | ✅ JSON 导入导出 |
| 数据清理 | ❌ 无 | ✅ 自动过期清理 |
| 表情 | 7 种 | ✅ 8 种（含睡眠） |
| 执行安全 | 基本 | ✅ 动作数限制、超时保护 |

## 使用

```bash
pip install -r requirements.txt
python main.py
```

或双击 `run.bat`。
