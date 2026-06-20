@echo off
chcp 65001 >nul
cd /d "%~dp0"
title 桌面精灵 V2 测试版
echo 🧠 桌面精灵 V2 测试版
echo ======================
echo.
echo 正在启动...
python main.py
if %errorlevel% neq 0 (
    echo.
    echo ❌ 启动失败，请安装依赖: pip install -r requirements.txt
    pause
)
