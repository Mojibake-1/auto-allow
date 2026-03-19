"""
⚡ Antigravity Auto Allow - 屏幕精灵 v3
========================================
兼容入口 — 实际代码已拆分到 auto_allow/ 包中

用法:
  python auto_allow.py          ← 兼容旧方式
  python -m auto_allow          ← 推荐新方式
"""

from auto_allow.app import AutoAllowApp

if __name__ == "__main__":
    app = AutoAllowApp()
    app.run()
