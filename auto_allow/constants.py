"""
路径常量与默认参数
"""

import os
import pyautogui

# ── 路径常量 ──────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".auto_allow")
TEMPLATES_DIR = os.path.join(CONFIG_DIR, "templates")
HISTORY_DIR = os.path.join(CONFIG_DIR, "history")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")
ICON_PATH = os.path.join(APP_DIR, "icon.ico")

MAX_HISTORY = 20
HISTORY_CROP_W = 520
HISTORY_CROP_H = 420

DEFAULT_INTERVAL = 2.0
DEFAULT_CONFIDENCE = 0.92
DEFAULT_COOLDOWN = 1.5

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.05
