@echo off
chcp 65001 >nul
title ⚡ Auto Allow 安装程序
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   ⚡ Auto Allow 屏幕精灵 - 安装     ║
echo  ╚══════════════════════════════════════╝
echo.
echo [1/3] 安装 Python 依赖...
pip install pyautogui Pillow opencv-python numpy pystray --quiet
if errorlevel 1 (
    echo ❌ 依赖安装失败，请确保已安装 Python 和 pip
    pause
    exit /b 1
)
echo ✅ 依赖安装完成
echo.

echo [2/3] 生成应用图标...
python -c "import sys; sys.path.insert(0, r'%~dp0'); from auto_allow import generate_icon; generate_icon(); print('OK')"
echo ✅ 图标已生成
echo.

echo [3/3] 创建桌面快捷方式...
powershell -ExecutionPolicy Bypass -File "%~dp0create_shortcut.ps1"
echo ✅ 桌面快捷方式已创建
echo.

echo ══════════════════════════════════════
echo  ✅ 安装完成！可以通过以下方式启动：
echo     1. 双击桌面「⚡ Auto Allow」快捷方式
echo     2. 双击本文件夹中的「启动.bat」
echo ══════════════════════════════════════
echo.
pause
