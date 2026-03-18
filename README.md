# ⚡ Auto Allow — 屏幕精灵

系统托盘常驻 + 浮窗控制 + 多模板屏幕匹配自动点击工具。

截取屏幕上的目标按钮作为模板，程序会持续扫描屏幕并自动点击匹配到的按钮。适用于需要频繁点击确认/允许按钮的场景。

## ✨ 功能

- 🎯 **屏幕截取** — 框选目标按钮，自动保存为匹配模板
- 🔄 **多模板支持** — 同时监控多个不同按钮
- 📊 **浮窗控件** — 悬停展开、离开折叠，呼吸灯脉冲动画
- 🖱 **自动点击** — OpenCV 模板匹配，可调置信度
- 📋 **点击历史** — 每次点击截图记录，方便回查
- ⚙ **参数可调** — 扫描间隔、匹配置信度、点击冷却
- 🔔 **系统托盘** — 后台常驻，右键菜单快捷操作

## 🚀 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Mojibake-1/auto-allow.git
cd auto-allow

# 2. 运行安装脚本（安装依赖 + 创建桌面快捷方式）
安装.bat
```

### 手动安装

```bash
pip install pyautogui Pillow opencv-python numpy pystray
```

## 📖 使用

1. 双击 `启动.bat` 或桌面快捷方式启动
2. 点击 📷 截取目标按钮模板
3. 点击 ▶ 开始监控
4. 程序会自动扫描屏幕并点击匹配按钮

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `auto_allow.py` | 主程序（Tkinter GUI + OpenCV 匹配） |
| `requirements.txt` | Python 依赖 |
| `安装.bat` | 一键安装脚本 |
| `启动.bat` | 启动脚本 |
| `卸载.bat` | 卸载脚本 |
| `AutoAllow.vbs` | 静默启动器（无黑窗） |
| `create_shortcut.ps1` | 桌面快捷方式生成 |
| `icon.ico` | 应用图标 |

## ⚙ 配置

用户配置保存在 `~/.auto_allow/`：
- `config.json` — 扫描间隔、置信度等参数
- `templates/` — 保存的按钮模板图片
- `history/` — 点击历史截图

## 📋 依赖

- Python 3.8+
- Windows 10/11
- pyautogui, Pillow, opencv-python, numpy, pystray

## 📄 License

MIT
