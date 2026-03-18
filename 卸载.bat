@echo off
chcp 65001 >nul
title ⚡ Auto Allow 卸载程序
echo.
echo  ╔══════════════════════════════════════╗
echo  ║   ⚡ Auto Allow 屏幕精灵 - 卸载     ║
echo  ╚══════════════════════════════════════╝
echo.

echo [1/3] 删除桌面快捷方式...
del "%USERPROFILE%\Desktop\Auto Allow.lnk" 2>nul
if exist "%USERPROFILE%\Desktop\Auto Allow.lnk" (
    echo ⚠ 快捷方式删除失败
) else (
    echo ✅ 桌面快捷方式已删除
)
echo.

echo [2/3] 清除配置和模板数据...
set /p confirm="是否删除所有已保存的模板和配置？(Y/N): "
if /i "%confirm%"=="Y" (
    rmdir /s /q "%USERPROFILE%\.auto_allow" 2>nul
    echo ✅ 配置数据已清除
) else (
    echo ⏭ 跳过，配置保留在 %USERPROFILE%\.auto_allow
)
echo.

echo [3/3] 卸载 Python 依赖（可选）...
set /p uninstall_deps="是否卸载相关 Python 包？(Y/N): "
if /i "%uninstall_deps%"=="Y" (
    pip uninstall pystray -y --quiet 2>nul
    echo ✅ 已卸载 pystray（其他通用包已保留）
) else (
    echo ⏭ 跳过
)
echo.

echo ══════════════════════════════════════
echo  ✅ 卸载完成！程序文件夹可手动删除。
echo ══════════════════════════════════════
echo.
pause
