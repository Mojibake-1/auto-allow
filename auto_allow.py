"""
⚡ Antigravity Auto Allow - 屏幕精灵 v3
========================================
系统托盘常驻 + 浮窗控制 + 多模板屏幕匹配自动点击
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyautogui
from PIL import Image, ImageTk, ImageGrab, ImageDraw, ImageFont
import cv2
import numpy as np
import pystray
from pystray import MenuItem as TrayItem
import threading
import time
import os
import json
import glob
import sys

# ── 路径常量 ──────────────────────────────────────────
APP_DIR = os.path.dirname(os.path.abspath(__file__))
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


# ══════════════════════════════════════════════════════
#  图标生成
# ══════════════════════════════════════════════════════
def generate_icon():
    """生成应用程序图标 (.ico)"""
    if os.path.exists(ICON_PATH):
        return Image.open(ICON_PATH)

    size = 256
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 渐变圆形背景
    for i in range(size // 2, 0, -1):
        t = i / (size // 2)
        r = int(80 + 28 * (1 - t))
        g = int(60 + 39 * (1 - t))
        b = int(220 + 35 * (1 - t))
        draw.ellipse([size // 2 - i, size // 2 - i,
                      size // 2 + i, size // 2 + i],
                     fill=(r, g, b, 255))

    # 闪电符号 ⚡
    bolt = [
        (128, 30), (75, 125), (115, 125),
        (95, 226), (180, 110), (135, 110), (158, 30)
    ]
    draw.polygon(bolt, fill=(255, 255, 255, 240))

    # 保存
    img.save(ICON_PATH, format='ICO',
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (256, 256)])
    return img


# ══════════════════════════════════════════════════════
#  屏幕截取覆盖层
# ══════════════════════════════════════════════════════
class ScreenCaptureOverlay(tk.Toplevel):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.screenshot = ImageGrab.grab()
        sw, sh = self.screenshot.size

        self.overrideredirect(True)
        self.geometry(f"{sw}x{sh}+0+0")
        self.attributes('-topmost', True)
        self.configure(cursor="cross")

        self.canvas = tk.Canvas(self, width=sw, height=sh, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        overlay = self.screenshot.copy().convert("RGBA")
        dark = Image.new("RGBA", (sw, sh), (0, 0, 0, 100))
        overlay = Image.alpha_composite(overlay, dark).convert("RGB")
        self._bg = ImageTk.PhotoImage(overlay)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self._bg)
        self.canvas.create_text(sw // 2, 40,
                                text="🎯 拖动鼠标框选目标按钮  |  ESC 取消",
                                fill="#ffd700",
                                font=("Microsoft YaHei", 18, "bold"))

        self.sx = self.sy = 0
        self.rect = None
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self.destroy())
        self.focus_force()

    def _press(self, e):
        self.sx, self.sy = e.x, e.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(e.x, e.y, e.x, e.y,
                                                  outline="#00ff88", width=2,
                                                  dash=(6, 3))

    def _drag(self, e):
        self.canvas.coords(self.rect, self.sx, self.sy, e.x, e.y)

    def _release(self, e):
        x1, y1 = min(self.sx, e.x), min(self.sy, e.y)
        x2, y2 = max(self.sx, e.x), max(self.sy, e.y)
        if x2 - x1 > 5 and y2 - y1 > 5:
            self.destroy()
            self.callback(self.screenshot.crop((x1, y1, x2, y2)))
        else:
            self.destroy()


# ══════════════════════════════════════════════════════
#  模板管理器
# ══════════════════════════════════════════════════════
class TemplateManager:
    def __init__(self):
        os.makedirs(TEMPLATES_DIR, exist_ok=True)
        self.templates = []   # [(name, pil, cv), ...]
        self.load_all()

    def load_all(self):
        self.templates = []
        for p in sorted(glob.glob(os.path.join(TEMPLATES_DIR, "*.png"))):
            try:
                name = os.path.splitext(os.path.basename(p))[0]
                pil = Image.open(p).convert("RGB")
                cv = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
                self.templates.append((name, pil, cv))
            except Exception:
                pass

    def add(self, pil_img, name=None):
        if name is None:
            i = len(self.templates) + 1
            while os.path.exists(os.path.join(TEMPLATES_DIR, f"模板{i}.png")):
                i += 1
            name = f"模板{i}"
        pil_img.save(os.path.join(TEMPLATES_DIR, f"{name}.png"))
        cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        self.templates.append((name, pil_img, cv))
        return name

    def remove(self, idx):
        if 0 <= idx < len(self.templates):
            name = self.templates[idx][0]
            p = os.path.join(TEMPLATES_DIR, f"{name}.png")
            if os.path.exists(p):
                os.remove(p)
            self.templates.pop(idx)

    def clear(self):
        while self.templates:
            self.remove(0)

    def count(self):
        return len(self.templates)

    def cv_list(self):
        return [(t[0], t[2]) for t in self.templates]

    def pil_list(self):
        return [(t[0], t[1]) for t in self.templates]


# ══════════════════════════════════════════════════════
#  浮窗控件（自动展开/折叠）
# ══════════════════════════════════════════════════════
class FloatingWidget(tk.Toplevel):
    """悬浮控制面板：鼠标悬停展开，离开后自动折叠为小圆角图标"""

    COLLAPSED_W = 52
    COLLAPSED_H = 52
    EXPANDED_W = 320
    EXPANDED_H = 200
    COLLAPSE_DELAY = 200   # 鼠标离开后多久折叠 (ms)

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c

        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.attributes('-alpha', 0.95)
        self.configure(bg=self.c['bg'])

        # 状态
        self.is_expanded = True
        self._collapse_timer = None
        self._status_color = self.c['dim']
        self._status_text = "待机中"
        self._count = 0
        self._tpl_count = 0
        self._last_action = "截取按钮模板后点击 ▶ 开始"
        self._offset_x = 0
        self._offset_y = 0
        self._pulse_phase = 0
        self._pulse_job = None

        # 初始位置：屏幕右下角
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        self._pos_x = scr_w - self.EXPANDED_W - 20
        self._pos_y = scr_h - self.EXPANDED_H - 80
        self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}"
                      f"+{self._pos_x}+{self._pos_y}")

        # 构建两种视图
        self.collapsed_frame = tk.Frame(self, bg=self.c['bg'])
        self.expanded_frame = tk.Frame(self, bg=self.c['bg'])
        self._build_collapsed_view()
        self._build_expanded_view()

        # 初始显示展开状态
        self.expanded_frame.pack(fill=tk.BOTH, expand=True)

        # 鼠标悬停追踪
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # 首次显示后设置圆角
        self.after(100, lambda: self._apply_rounded_corners(8))

        # 3 秒后自动折叠（给用户时间看到界面）
        self._collapse_timer = self.after(2500, self._collapse)

    # ── 圆角 / 圆形（Windows API）─────────────────
    def _apply_rounded_corners(self, radius):
        try:
            import ctypes
            hwnd = int(self.winfo_id())
            w = self.winfo_width()
            h = self.winfo_height()
            rgn = ctypes.windll.gdi32.CreateRoundRectRgn(
                0, 0, w + 1, h + 1, radius, radius)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    def _apply_circular_region(self):
        try:
            import ctypes
            hwnd = int(self.winfo_id())
            w = self.winfo_width()
            h = self.winfo_height()
            rgn = ctypes.windll.gdi32.CreateEllipticRgn(0, 0, w + 1, h + 1)
            ctypes.windll.user32.SetWindowRgn(hwnd, rgn, True)
        except Exception:
            pass

    # ── 生成渐变圆形图标 ──────────────────────────────
    def _render_orb(self, size, glow_alpha=180):
        """用 PIL 渲染发光渐变圆球图标"""
        # 背景使用色键颜色，配合 transparentcolor 实现透明
        chroma = (1, 1, 1)
        img = Image.new('RGB', (size, size), chroma)
        draw = ImageDraw.Draw(img)

        cx, cy = size // 2, size // 2
        r = size // 2 - 2

        # 外圈光晕
        for i in range(r, r - 6, -1):
            t_glow = (i - (r - 6)) / 6
            draw.ellipse([cx - i, cy - i, cx + i, cy + i],
                         fill=(int(108 * t_glow + chroma[0] * (1 - t_glow)),
                               int(99 * t_glow + chroma[1] * (1 - t_glow)),
                               int(255 * t_glow + chroma[2] * (1 - t_glow))))

        # 渐变填充圆
        for i in range(r - 4, 0, -1):
            t = i / (r - 4)
            red = int(90 + 40 * (1 - t))
            grn = int(70 + 50 * (1 - t))
            blu = int(240 - 20 * (1 - t))
            draw.ellipse([cx - i, cy - i, cx + i, cy + i],
                         fill=(red, grn, blu, 255))

        # 高光
        hr = r // 3
        for i in range(hr, 0, -1):
            blend = 0.3 * (1 - i / hr)
            # 在圆心左上方画白色高光
            base_r, base_g, base_b = 130, 120, 220
            pr = int(base_r + (255 - base_r) * blend)
            pg = int(base_g + (255 - base_g) * blend)
            pb = int(base_b + (255 - base_b) * blend)
            draw.ellipse([cx - hr + 2 - i, cy - hr - 2 - i,
                          cx - hr + 2 + i, cy - hr - 2 + i],
                         fill=(pr, pg, pb))

        # ⚡ 闪电
        s = size / 72  # scale factor
        bolt = [
            (int(36 * s), int(12 * s)), (int(24 * s), int(35 * s)),
            (int(33 * s), int(35 * s)), (int(28 * s), int(58 * s)),
            (int(48 * s), int(30 * s)), (int(38 * s), int(30 * s)),
            (int(44 * s), int(12 * s)),
        ]
        draw.polygon(bolt, fill=(255, 255, 255))

        return img

    # ── 折叠视图 ──────────────────────────────────────
    def _build_collapsed_view(self):
        c = self.c
        f = self.collapsed_frame
        sz = self.COLLAPSED_W

        # Canvas 作为容器，背景用色键颜色
        self.mini_canvas = tk.Canvas(f, width=sz, height=sz,
                                      bg='#010101', highlightthickness=0,
                                      cursor="hand2")
        self.mini_canvas.pack(fill=tk.BOTH, expand=True)

        # 渲染基础圆球图标
        self._orb_base = self._render_orb(sz, glow_alpha=180)
        self._orb_tk = ImageTk.PhotoImage(self._orb_base)
        self._orb_canvas_id = self.mini_canvas.create_image(
            sz // 2, sz // 2, image=self._orb_tk)

        # 状态环（用圆弧表示）
        pad = 3
        self._ring_id = self.mini_canvas.create_oval(
            pad, pad, sz - pad, sz - pad,
            outline=c['dim'], width=2, dash=(4, 4))

        # 拖动
        self.mini_canvas.bind("<Button-1>", self._start_drag)
        self.mini_canvas.bind("<B1-Motion>", self._do_drag)

    # ── 展开视图 ──────────────────────────────────────
    def _build_expanded_view(self):
        c = self.c

        border = tk.Frame(self.expanded_frame, bg=c['border'], bd=0)
        border.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        main = tk.Frame(border, bg=c['bg'])
        main.pack(fill=tk.BOTH, expand=True)

        # ── 标题栏（可拖动）──
        title_bar = tk.Frame(main, bg=c['card'], height=30)
        title_bar.pack(fill=tk.X)
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text="  ⚡ Auto Allow",
                 font=("Segoe UI", 10, "bold"),
                 fg=c['accent'], bg=c['card']).pack(side=tk.LEFT)

        # 关闭按钮（隐藏到托盘）
        close_btn = tk.Label(title_bar, text=" ✕ ",
                              font=("Consolas", 10),
                              fg=c['dim'], bg=c['card'], cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(0, 4))
        close_btn.bind("<Button-1>", lambda e: self.hide())
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=c['danger']))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=c['dim']))

        # 拖动绑定
        title_bar.bind("<Button-1>", self._start_drag)
        title_bar.bind("<B1-Motion>", self._do_drag)

        # ── 状态行 ──
        status_row = tk.Frame(main, bg=c['bg'])
        status_row.pack(fill=tk.X, padx=12, pady=(8, 2))

        self.dot = tk.Canvas(status_row, width=12, height=12,
                              bg=c['bg'], highlightthickness=0)
        self.dot.pack(side=tk.LEFT)
        self._dot_id = self.dot.create_oval(1, 1, 11, 11, fill=c['dim'],
                                             outline='')

        self.status_lbl = tk.Label(status_row, text="待机中",
                                    font=("Microsoft YaHei", 10),
                                    fg=c['dim'], bg=c['bg'])
        self.status_lbl.pack(side=tk.LEFT, padx=(6, 0))

        self.count_lbl = tk.Label(status_row, text="🖱 0",
                                   font=("Segoe UI", 10, "bold"),
                                   fg=c['warning'], bg=c['bg'])
        self.count_lbl.pack(side=tk.RIGHT)

        self.tpl_lbl = tk.Label(status_row, text="📌 0模板",
                                 font=("Microsoft YaHei", 9),
                                 fg=c['dim'], bg=c['bg'])
        self.tpl_lbl.pack(side=tk.RIGHT, padx=(0, 10))

        # ── 按钮行 ──
        btn_row = tk.Frame(main, bg=c['bg'])
        btn_row.pack(fill=tk.X, padx=12, pady=(6, 4))

        self.toggle_btn = tk.Button(
            btn_row, text="▶  开始", font=("Microsoft YaHei", 11, "bold"),
            fg='#fff', bg=c['success'], activebackground='#00c080',
            activeforeground='#fff', bd=0, padx=14, pady=4, cursor="hand2",
            command=self.app.toggle_monitoring)
        self.toggle_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        for emoji, bg_c, fg_c, cmd in [
            ("📷", c['accent'],  '#fff',     self.app.start_capture),
            ("🔍", c['card'],    c['warning'], self.app.test_scan),
            ("📋", c['card'],    c['fg'],     self.app.view_history),
            ("⚙",  c['card'],    c['dim'],    self.app.show_settings),
        ]:
            tk.Frame(btn_row, width=5, bg=c['bg']).pack(side=tk.LEFT)
            tk.Button(btn_row, text=emoji, font=("Segoe UI", 11),
                      fg=fg_c, bg=bg_c, activebackground=c['border'],
                      bd=0, padx=6, pady=2, cursor="hand2",
                      command=cmd).pack(side=tk.LEFT)

        # ── 最近动作 ──
        self.last_lbl = tk.Label(main, text="截取按钮模板后点击 ▶ 开始",
                                  font=("Microsoft YaHei", 8),
                                  fg=c['dim'], bg=c['bg'], anchor='w')
        self.last_lbl.pack(fill=tk.X, padx=12, pady=(3, 7))

    # ── 展开/折叠逻辑 ────────────────────────────────
    def _on_enter(self, e):
        # 取消折叠定时器
        if self._collapse_timer:
            self.after_cancel(self._collapse_timer)
            self._collapse_timer = None
        if not self.is_expanded:
            self._expand()

    def _on_leave(self, e):
        # 检查鼠标是否真的离开了窗口区域
        try:
            mx, my = self.winfo_pointerxy()
            wx = self.winfo_rootx()
            wy = self.winfo_rooty()
            ww = self.winfo_width()
            wh = self.winfo_height()
            if wx <= mx <= wx + ww and wy <= my <= wy + wh:
                return  # 鼠标还在窗口内（移到子控件上了）
        except Exception:
            pass

        if self.is_expanded and self._collapse_timer is None:
            self._collapse_timer = self.after(self.COLLAPSE_DELAY,
                                               self._collapse)

    def _expand(self):
        self.is_expanded = True
        self.collapsed_frame.pack_forget()
        self.expanded_frame.pack(fill=tk.BOTH, expand=True)

        # 同步状态到展开视图
        self.status_lbl.configure(text=self._status_text, fg=self._status_color)
        self.dot.itemconfig(self._dot_id, fill=self._status_color)
        self.count_lbl.configure(text=f"🖱 {self._count}")
        self.tpl_lbl.configure(text=f"📌 {self._tpl_count}模板")
        self.last_lbl.configure(text=self._last_action)

        # 重新设置监控按钮状态
        if self.app.monitoring:
            self.toggle_btn.configure(text="⏹ 停止", bg=self.c['danger'],
                                       activebackground='#ee5555')
        else:
            self.toggle_btn.configure(text="▶  开始", bg=self.c['success'],
                                       activebackground='#00c080')

        x, y = self.winfo_x(), self.winfo_y()
        # 保证不超出屏幕
        scr_w = self.winfo_screenwidth()
        scr_h = self.winfo_screenheight()
        x = min(x, scr_w - self.EXPANDED_W - 5)
        y = min(y, scr_h - self.EXPANDED_H - 5)
        self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}+{x}+{y}")
        # 取消透明色键
        try:
            self.attributes('-transparentcolor', '')
        except Exception:
            pass
        self.attributes('-alpha', 0.95)
        self.after(20, lambda: self._apply_rounded_corners(8))

    def _collapse(self):
        self._collapse_timer = None
        self.is_expanded = False
        self.expanded_frame.pack_forget()
        self.collapsed_frame.pack(fill=tk.BOTH, expand=True)

        # 更新状态环颜色
        self.mini_canvas.itemconfig(self._ring_id, outline=self._status_color)

        x, y = self.winfo_x(), self.winfo_y()
        self.geometry(f"{self.COLLAPSED_W}x{self.COLLAPSED_H}+{x}+{y}")
        # 启用透明色键，让四角完全透明
        try:
            self.attributes('-transparentcolor', '#010101')
        except Exception:
            pass
        self.after(20, self._apply_circular_region)

        # 启动脉冲动画（监控中时）
        if self.app.monitoring:
            self._start_pulse()

    # ── 脉冲动画 ──────────────────────────────────────
    def _start_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
        self._pulse_phase = 0
        self._do_pulse()

    def _stop_pulse(self):
        if self._pulse_job:
            self.after_cancel(self._pulse_job)
            self._pulse_job = None
        # 恢复默认外观
        if not self.is_expanded:
            self.mini_canvas.itemconfig(self._ring_id, width=2)
            self.attributes('-alpha', 0.95)

    def _do_pulse(self):
        """呼吸灯脉冲效果"""
        if self.is_expanded or not self.app.monitoring:
            self._pulse_job = None
            return

        import math
        self._pulse_phase += 0.08
        # 呼吸效果：alpha 在 0.7~1.0 之间变化
        val = (math.sin(self._pulse_phase) + 1) / 2  # 0~1
        alpha = 0.70 + 0.30 * val
        ring_width = 2 + int(3 * val)

        try:
            self.attributes('-alpha', alpha)
            self.mini_canvas.itemconfig(self._ring_id, width=ring_width)
        except Exception:
            pass

        self._pulse_job = self.after(50, self._do_pulse)

    # ── 拖动 ──────────────────────────────────────────
    def _start_drag(self, e):
        self._offset_x = e.x
        self._offset_y = e.y

    def _do_drag(self, e):
        x = self.winfo_x() + e.x - self._offset_x
        y = self.winfo_y() + e.y - self._offset_y
        if self.is_expanded:
            self.geometry(f"{self.EXPANDED_W}x{self.EXPANDED_H}+{x}+{y}")
        else:
            self.geometry(f"{self.COLLAPSED_W}x{self.COLLAPSED_H}+{x}+{y}")

    # ── 显示/隐藏 ────────────────────────────────────
    def show(self):
        self.deiconify()
        self.lift()

    def hide(self):
        self.withdraw()

    # ── 状态更新（同时更新内部缓存和当前可见的 UI）────
    def set_status(self, text, color):
        self._status_text = text
        self._status_color = color
        if self.is_expanded:
            self.status_lbl.configure(text=text, fg=color)
            self.dot.itemconfig(self._dot_id, fill=color)
        else:
            self.mini_canvas.itemconfig(self._ring_id, outline=color)

    def set_monitoring_ui(self, active):
        if self.is_expanded:
            if active:
                self.toggle_btn.configure(text="⏹ 停止", bg=self.c['danger'],
                                           activebackground='#ee5555')
            else:
                self.toggle_btn.configure(text="▶  开始",
                                           bg=self.c['success'],
                                           activebackground='#00c080')
        if active and not self.is_expanded:
            self._start_pulse()
        elif not active:
            self._stop_pulse()

    def update_count(self, n):
        self._count = n
        if self.is_expanded:
            self.count_lbl.configure(text=f"🖱 {n}")

    def update_template_count(self, n):
        self._tpl_count = n
        if self.is_expanded:
            self.tpl_lbl.configure(text=f"📌 {n}模板")

    def set_last_action(self, text):
        self._last_action = text
        if self.is_expanded:
            self.last_lbl.configure(text=text)


# ══════════════════════════════════════════════════════
#  设置对话框
# ══════════════════════════════════════════════════════
class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c
        self.title("⚙ Auto Allow 设置")
        self.geometry("460x560")
        self.resizable(False, False)
        self.attributes('-topmost', True)
        self.configure(bg=self.c['bg'])

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        c = self.c

        # ── 模板管理 ──
        tk.Label(self, text="🎯 目标按钮模板",
                 font=("Microsoft YaHei", 12, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(anchor='w', padx=16, pady=(12, 6))

        list_outer = tk.Frame(self, bg=c['border'])
        list_outer.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 6))

        list_inner = tk.Frame(list_outer, bg=c['card'])
        list_inner.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 可滚动区域
        canvas = tk.Canvas(list_inner, bg=c['card'], highlightthickness=0,
                           height=200)
        scrollbar = tk.Scrollbar(list_inner, orient=tk.VERTICAL,
                                  command=canvas.yview)
        self.tpl_frame = tk.Frame(canvas, bg=c['card'])

        self.tpl_frame.bind("<Configure>",
                             lambda e: canvas.configure(
                                 scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.tpl_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 按钮行
        btn_row = tk.Frame(self, bg=c['bg'])
        btn_row.pack(fill=tk.X, padx=16, pady=(0, 8))

        for text, cmd, bg_c in [
            ("📷 截取新模板", self._capture, c['accent']),
            ("🗑 删除选中", self._remove, c['card']),
            ("🗑 全部清除", self._clear, c['card']),
        ]:
            tk.Button(btn_row, text=text, font=("Microsoft YaHei", 9),
                      fg='#fff' if bg_c == c['accent'] else c['dim'],
                      bg=bg_c, activebackground=c['accent_h'] if bg_c == c['accent'] else c['border'],
                      bd=0, padx=10, pady=4, cursor="hand2",
                      command=cmd).pack(side=tk.LEFT, padx=(0, 6))

        # ── 参数设置 ──
        tk.Label(self, text="⚙ 参数设置",
                 font=("Microsoft YaHei", 12, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(anchor='w', padx=16, pady=(4, 6))

        params = tk.Frame(self, bg=c['card'], highlightbackground=c['border'],
                          highlightthickness=1)
        params.pack(fill=tk.X, padx=16, pady=(0, 8))

        self._slider_row(params, "扫描间隔（秒）", self.app.interval, 0.5, 10.0)
        self._slider_row(params, "匹配置信度", self.app.confidence, 0.70, 1.0)
        self._slider_row(params, "点击冷却（秒）", self.app.cooldown, 0.5, 15.0)
        tk.Frame(params, bg=c['card'], height=6).pack()

        # 保存按钮
        tk.Button(self, text="💾 保存设置", font=("Microsoft YaHei", 10, "bold"),
                  fg='#fff', bg=c['success'], activebackground='#00c080',
                  bd=0, padx=20, pady=6, cursor="hand2",
                  command=self._save).pack(pady=(0, 12))

        self._refresh_list()

    def _slider_row(self, parent, label, var, lo, hi):
        c = self.c
        row = tk.Frame(parent, bg=c['card'])
        row.pack(fill=tk.X, padx=12, pady=2)
        tk.Label(row, text=label, font=("Microsoft YaHei", 9),
                 fg=c['fg'], bg=c['card'], width=16, anchor='w').pack(side=tk.LEFT)
        tk.Scale(row, from_=lo, to=hi, resolution=0.05, orient=tk.HORIZONTAL,
                 variable=var, bg=c['card'], fg=c['fg'],
                 troughcolor=c['input'], highlightthickness=0, bd=0,
                 length=200, font=("Consolas", 8),
                 activebackground=c['accent']).pack(side=tk.RIGHT, fill=tk.X,
                                                     expand=True)

    def _refresh_list(self):
        for w in self.tpl_frame.winfo_children():
            w.destroy()
        c = self.c
        templates = self.app.tpl_mgr.pil_list()
        self._thumbs = []
        self.sel_idx = tk.IntVar(value=-1)

        if not templates:
            tk.Label(self.tpl_frame, text="📭 还没有模板",
                     font=("Microsoft YaHei", 10), fg=c['dim'],
                     bg=c['card']).pack(pady=20)
            return

        for idx, (name, pil) in enumerate(templates):
            row = tk.Frame(self.tpl_frame, bg=c['input'])
            row.pack(fill=tk.X, pady=1, padx=4)

            tk.Radiobutton(row, variable=self.sel_idx, value=idx,
                           bg=c['input'], fg=c['fg'],
                           selectcolor=c['input'],
                           activebackground=c['input']).pack(side=tk.LEFT, padx=4)

            ratio = min(100 / max(pil.width, 1), 30 / max(pil.height, 1), 2.0)
            tw, th = max(int(pil.width * ratio), 1), max(int(pil.height * ratio), 1)
            thumb = ImageTk.PhotoImage(pil.resize((tw, th), Image.LANCZOS))
            self._thumbs.append(thumb)
            tk.Label(row, image=thumb, bg=c['input']).pack(side=tk.LEFT, padx=4)

            tk.Label(row, text=f"{name}  ({pil.width}×{pil.height})",
                     font=("Microsoft YaHei", 9), fg=c['fg'],
                     bg=c['input']).pack(side=tk.LEFT, padx=4)

    def _capture(self):
        self.withdraw()
        self.app.start_capture(on_done=lambda: self._on_return())

    def _on_return(self):
        self.deiconify()
        self._refresh_list()

    def _remove(self):
        if not hasattr(self, 'sel_idx'):
            return
        idx = self.sel_idx.get()
        if 0 <= idx < self.app.tpl_mgr.count():
            self.app.tpl_mgr.remove(idx)
            self._refresh_list()
            self.app.widget.update_template_count(self.app.tpl_mgr.count())

    def _clear(self):
        if self.app.tpl_mgr.count() == 0:
            return
        if messagebox.askyesno("确认", "删除所有模板？", parent=self):
            self.app.tpl_mgr.clear()
            self._refresh_list()
            self.app.widget.update_template_count(0)

    def _save(self):
        self.app.save_config()
        self._close()

    def _close(self):
        self.app.save_config()
        self.destroy()
        self.app.settings_win = None


# ══════════════════════════════════════════════════════
#  历史记录查看器
# ══════════════════════════════════════════════════════
class HistoryViewer(tk.Toplevel):
    """点击历史截图查看器"""

    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.c = app.c
        self.title("📋 点击历史截图")
        self.geometry("560x620")
        self.resizable(False, True)
        self.attributes('-topmost', True)
        self.configure(bg=self.c['bg'])

        self._thumbs = []
        self._build()

    def _build(self):
        c = self.c

        # 标题
        hdr = tk.Frame(self, bg=c['bg'])
        hdr.pack(fill=tk.X, padx=16, pady=(12, 6))

        tk.Label(hdr, text="📋 点击历史截图",
                 font=("Microsoft YaHei", 13, "bold"),
                 fg=c['fg'], bg=c['bg']).pack(side=tk.LEFT)

        count = len(self.app.click_history)
        tk.Label(hdr, text=f"共 {count} / {MAX_HISTORY} 条",
                 font=("Microsoft YaHei", 10),
                 fg=c['dim'], bg=c['bg']).pack(side=tk.RIGHT)

        # 可滚动区域
        container = tk.Frame(self, bg=c['bg'])
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 12))

        canvas = tk.Canvas(container, bg=c['bg'], highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient=tk.VERTICAL,
                                  command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg=c['bg'])

        self.scroll_frame.bind("<Configure>",
                                lambda e: canvas.configure(
                                    scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 鼠标滚轮绑定
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-e.delta // 120, "units"))

        # 填充历史记录（最新的在上面）
        if not self.app.click_history:
            tk.Label(self.scroll_frame, text="📭 还没有点击记录\n开始监控后会自动保存",
                     font=("Microsoft YaHei", 11), fg=c['dim'],
                     bg=c['bg']).pack(pady=40)
            return

        for ts, filepath, name, idx in reversed(self.app.click_history):
            self._add_history_item(ts, filepath, name, idx)

        # 提示
        tk.Label(self, text="💡 点击截图可查看原始大小  |  截图保存在 ~/.auto_allow/history/",
                 font=("Microsoft YaHei", 8), fg=c['dim'],
                 bg=c['bg']).pack(pady=(0, 8))

    def _add_history_item(self, ts, filepath, name, idx):
        c = self.c

        card = tk.Frame(self.scroll_frame, bg=c['card'],
                        highlightbackground=c['border'],
                        highlightthickness=1)
        card.pack(fill=tk.X, pady=3)

        # 标题行
        info = tk.Frame(card, bg=c['card'])
        info.pack(fill=tk.X, padx=8, pady=(6, 2))

        tk.Label(info, text=f"#{idx}", font=("Consolas", 9, "bold"),
                 fg=c['accent'], bg=c['card']).pack(side=tk.LEFT)
        tk.Label(info, text=f"  [{ts}]  「{name}」",
                 font=("Microsoft YaHei", 9), fg=c['fg'],
                 bg=c['card']).pack(side=tk.LEFT)

        # 缩略图
        try:
            if os.path.exists(filepath):
                pil = Image.open(filepath).convert("RGB")
                # 缩放到预览大小
                ratio = min(500 / max(pil.width, 1),
                           160 / max(pil.height, 1), 1.0)
                tw = max(int(pil.width * ratio), 1)
                th = max(int(pil.height * ratio), 1)
                thumb = ImageTk.PhotoImage(pil.resize((tw, th), Image.LANCZOS))
                self._thumbs.append(thumb)

                img_label = tk.Label(card, image=thumb, bg=c['card'],
                                      cursor="hand2")
                img_label.pack(padx=8, pady=(2, 6))

                # 点击打开原图
                fp = filepath  # 闭包捕获
                img_label.bind("<Button-1>",
                               lambda e, p=fp: os.startfile(p))
            else:
                tk.Label(card, text="(截图文件已删除)",
                         font=("Microsoft YaHei", 9), fg=c['dim'],
                         bg=c['card']).pack(padx=8, pady=6)
        except Exception as ex:
            tk.Label(card, text=f"(加载失败: {str(ex)[:30]})",
                     font=("Microsoft YaHei", 9), fg=c['danger'],
                     bg=c['card']).pack(padx=8, pady=6)


# ══════════════════════════════════════════════════════
#  主应用
# ══════════════════════════════════════════════════════
class AutoAllowApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()   # 主窗口隐藏，只用浮窗和托盘

        # 颜色主题
        self.c = {
            'bg': '#0f0f1a', 'card': '#1a1a2e', 'input': '#252540',
            'fg': '#e0e0f0', 'dim': '#8888aa',
            'accent': '#6c63ff', 'accent_h': '#7c73ff',
            'success': '#00d68f', 'danger': '#ff6b6b',
            'warning': '#ffd93d', 'border': '#2a2a4a',
        }

        # 状态
        self.monitoring = False
        self.click_count = 0
        self.running = True
        self.last_click_time = {}
        self.settings_win = None
        self._capture_callback = None

        # 配置变量
        self.interval = tk.DoubleVar(value=DEFAULT_INTERVAL)
        self.confidence = tk.DoubleVar(value=DEFAULT_CONFIDENCE)
        self.cooldown = tk.DoubleVar(value=DEFAULT_COOLDOWN)

        # 初始化
        os.makedirs(CONFIG_DIR, exist_ok=True)
        os.makedirs(HISTORY_DIR, exist_ok=True)
        self.icon_img = generate_icon()
        self.tpl_mgr = TemplateManager()
        self.click_history = []   # [(timestamp, filepath, name, idx), ...]
        self._load_history()
        self._load_config()

        # 创建 UI
        self.widget = FloatingWidget(self)
        self.widget.update_template_count(self.tpl_mgr.count())
        self._create_tray()

        # 全局热键
        self.root.bind_all("<F6>", lambda e: self.toggle_monitoring())

    # ── 系统托盘 ──────────────────────────────────────
    def _create_tray(self):

        def _make_menu():
            return pystray.Menu(
                TrayItem("显示 / 隐藏浮窗", self._tray_toggle_widget,
                         default=True),
                pystray.Menu.SEPARATOR,
                TrayItem("▶ 开始监控", self._tray_start,
                         visible=lambda item: not self.monitoring),
                TrayItem("⏹ 停止监控", self._tray_stop,
                         visible=lambda item: self.monitoring),
                pystray.Menu.SEPARATOR,
                TrayItem("📷 截取新模板", self._tray_capture),
                TrayItem("⚙ 设置...", self._tray_settings),
                pystray.Menu.SEPARATOR,
                TrayItem("❌ 退出", self._tray_quit),
            )

        self.tray = pystray.Icon(
            "auto_allow", self.icon_img, "⚡ Auto Allow", _make_menu())

        threading.Thread(target=self.tray.run, daemon=True).start()

    def _tray_toggle_widget(self):
        self.root.after(0, self._do_toggle_widget)

    def _do_toggle_widget(self):
        if self.widget.winfo_viewable():
            self.widget.hide()
        else:
            self.widget.show()

    def _tray_start(self):
        self.root.after(0, lambda: self._start_monitoring())

    def _tray_stop(self):
        self.root.after(0, lambda: self._stop_monitoring())

    def _tray_capture(self):
        self.root.after(0, lambda: self.start_capture())

    def _tray_settings(self):
        self.root.after(0, lambda: self.show_settings())

    def _tray_quit(self):
        self.root.after(0, lambda: self._quit())

    # ── 公共操作 ──────────────────────────────────────
    def toggle_monitoring(self):
        if self.monitoring:
            self._stop_monitoring()
        else:
            self._start_monitoring()

    def _start_monitoring(self):
        if self.tpl_mgr.count() == 0:
            messagebox.showwarning("提示", "请先截取至少一个目标按钮模板！")
            return
        self.monitoring = True
        self.last_click_time = {}
        self.widget.set_monitoring_ui(True)
        self.widget.set_status("监控中...", self.c['success'])
        self.widget.set_last_action(
            f"正在扫描 {self.tpl_mgr.count()} 个模板...")
        self._update_tray_tooltip("监控中...")
        threading.Thread(target=self._monitor_loop, daemon=True).start()

    def _stop_monitoring(self):
        self.monitoring = False
        self.widget.set_monitoring_ui(False)
        self.widget.set_status("已暂停", self.c['dim'])
        self.widget.set_last_action("已暂停监控")
        self._update_tray_tooltip("已暂停")

    def _update_tray_tooltip(self, status):
        try:
            self.tray.title = f"⚡ Auto Allow - {status}"
        except Exception:
            pass

    def start_capture(self, on_done=None):
        self._capture_callback = on_done
        self.widget.hide()
        if self.settings_win:
            self.settings_win.withdraw()
        self.root.after(300, self._do_capture)

    def _do_capture(self):
        ScreenCaptureOverlay(self.root, self._on_captured)

    def _on_captured(self, region):
        name = self.tpl_mgr.add(region)
        self.widget.show()
        self.widget.update_template_count(self.tpl_mgr.count())
        self.widget.set_last_action(
            f"✅ 已添加「{name}」({region.width}×{region.height})")
        self.save_config()
        if self._capture_callback:
            self._capture_callback()
            self._capture_callback = None

    def test_scan(self):
        """测试扫描：截屏一次，标出所有匹配位置，显示预览"""
        if self.tpl_mgr.count() == 0:
            messagebox.showwarning("提示", "请先截取至少一个模板！")
            return

        self.widget.set_last_action("🔍 正在测试扫描...")
        screenshot = ImageGrab.grab()
        screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        threshold = self.confidence.get()

        # 在截图副本上画标记
        marked = screenshot.copy()
        draw = ImageDraw.Draw(marked)
        matches = []

        for name, tpl_cv in self.tpl_mgr.cv_list():
            th, tw = tpl_cv.shape[:2]
            sh, sw = screen_cv.shape[:2]
            if tw > sw or th > sh:
                continue

            result = cv2.matchTemplate(screen_cv, tpl_cv,
                                        cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            x1, y1 = max_loc
            x2, y2 = x1 + tw, y1 + th

            if max_val >= threshold:
                # 超过阈值 → 绿框 + 会被点击
                draw.rectangle([x1, y1, x2, y2], outline="#00ff00", width=3)
                label = f"✅ {name}: {max_val:.3f}"
                draw.text((x1, y1 - 18), label, fill="#00ff00")
                matches.append((name, max_val, "✅ 会点击"))
            elif max_val >= 0.70:
                # 接近阈值 → 黄框 + 不会点
                draw.rectangle([x1, y1, x2, y2], outline="#ffdd00", width=2)
                label = f"⚠ {name}: {max_val:.3f}"
                draw.text((x1, y1 - 18), label, fill="#ffdd00")
                matches.append((name, max_val, "⚠ 不点击(低于阈值)"))
            else:
                matches.append((name, max_val, "❌ 未匹配"))

        # 显示预览窗口
        self._show_test_preview(marked, matches, threshold)

    def _show_test_preview(self, marked_img, matches, threshold):
        """显示测试扫描结果的预览窗口"""
        preview = tk.Toplevel(self.root)
        preview.title("🔍 测试扫描结果")
        preview.attributes('-topmost', True)
        preview.configure(bg=self.c['bg'])

        # 缩放图片以适合屏幕
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        scale = min((sw * 0.7) / marked_img.width,
                    (sh * 0.6) / marked_img.height, 1.0)
        pw = int(marked_img.width * scale)
        ph = int(marked_img.height * scale)
        resized = marked_img.resize((pw, ph), Image.LANCZOS)

        preview.geometry(f"{pw + 20}x{ph + 150}")

        # 图片
        preview._img = ImageTk.PhotoImage(resized)
        tk.Label(preview, image=preview._img, bg=self.c['bg']).pack(
            padx=10, pady=(10, 5))

        # 匹配结果列表
        info_frame = tk.Frame(preview, bg=self.c['card'])
        info_frame.pack(fill=tk.X, padx=10, pady=5)

        tk.Label(info_frame, text=f"阈值: {threshold:.2f}",
                 font=("Microsoft YaHei", 10, "bold"),
                 fg=self.c['fg'], bg=self.c['card']).pack(anchor='w', padx=8, pady=4)

        for name, val, status in matches:
            color = self.c['success'] if "✅" in status else (
                self.c['warning'] if "⚠" in status else self.c['dim'])
            tk.Label(info_frame,
                     text=f"  {status}  「{name}」 置信度: {val:.4f}",
                     font=("Consolas", 9), fg=color,
                     bg=self.c['card'], anchor='w').pack(fill=tk.X, padx=8)

        tk.Frame(info_frame, bg=self.c['card'], height=6).pack()

        # 提示
        tip = "💡 绿框=会被点击  黄框=接近但低于阈值  看不到框=完全不匹配"
        tk.Label(preview, text=tip, font=("Microsoft YaHei", 8),
                 fg=self.c['dim'], bg=self.c['bg']).pack(pady=(0, 8))

        self.widget.set_last_action(f"🔍 测试完成: {len([m for m in matches if '✅' in m[2]])} 个匹配")

    def view_history(self):
        """打开点击历史截图查看器"""
        HistoryViewer(self)

    def show_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        self.settings_win = SettingsDialog(self)

    def _quit(self):
        self.running = False
        self.monitoring = False
        self.save_config()
        try:
            self.tray.stop()
        except Exception:
            pass
        self.root.destroy()

    # ── 核心监控循环 ──────────────────────────────────
    def _monitor_loop(self):
        while self.monitoring and self.running:
            try:
                screenshot = ImageGrab.grab()
                screen_cv = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
                threshold = self.confidence.get()
                cd = self.cooldown.get()
                now = time.time()

                for name, tpl_cv in self.tpl_mgr.cv_list():
                    if name in self.last_click_time:
                        if now - self.last_click_time[name] < cd:
                            continue

                    th, tw = tpl_cv.shape[:2]
                    sh, sw = screen_cv.shape[:2]
                    if tw > sw or th > sh:
                        continue

                    result = cv2.matchTemplate(screen_cv, tpl_cv,
                                                cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(result)

                    if max_val >= threshold:
                        cx = max_loc[0] + tw // 2
                        cy = max_loc[1] + th // 2

                        # 保存点击上下文截图（点击前截取）
                        snap_path = self._save_click_snapshot(
                            screenshot, max_loc, tw, th, name)

                        pyautogui.click(cx, cy)

                        self.last_click_time[name] = time.time()
                        self.click_count += 1

                        ts = time.strftime("%H:%M:%S")
                        self.root.after(0, self._on_clicked,
                                        name, cx, cy, max_val, ts,
                                        snap_path)
                        time.sleep(0.5)
                        break

                time.sleep(self.interval.get())

            except pyautogui.FailSafeException:
                self.root.after(0, self._emergency_stop)
                return
            except Exception as e:
                self.root.after(0, self.widget.set_last_action,
                                f"⚠ 错误: {str(e)[:40]}")
                time.sleep(3)

    def _save_click_snapshot(self, screenshot, loc, tw, th, name):
        """以匹配区域为中心截取上下文截图，保留最近 MAX_HISTORY 张"""
        try:
            sw, sh = screenshot.size
            # 以按钮为中心，向上多截一些（看到命令内容）
            cx, cy = loc[0] + tw // 2, loc[1] + th // 2
            x1 = max(cx - HISTORY_CROP_W // 2, 0)
            y1 = max(cy - HISTORY_CROP_H * 2 // 3, 0)  # 上方多截
            x2 = min(x1 + HISTORY_CROP_W, sw)
            y2 = min(y1 + HISTORY_CROP_H, sh)

            crop = screenshot.crop((x1, y1, x2, y2))

            ts_file = time.strftime("%Y%m%d_%H%M%S")
            filename = f"{ts_file}_{name}.png"
            filepath = os.path.join(HISTORY_DIR, filename)
            crop.save(filepath)

            ts_display = time.strftime("%H:%M:%S")
            self.click_history.append((ts_display, filepath, name,
                                       self.click_count))

            # 只保留最近 MAX_HISTORY 条
            if len(self.click_history) > MAX_HISTORY:
                old = self.click_history.pop(0)
                try:
                    if os.path.exists(old[1]):
                        os.remove(old[1])
                except Exception:
                    pass

            return filepath
        except Exception:
            return None

    def _on_clicked(self, name, x, y, conf, ts, snap_path=None):
        self.widget.update_count(self.click_count)
        self.widget.set_status(f"✅ 点击了「{name}」", self.c['warning'])
        self.widget.set_last_action(
            f"[{ts}] 🖱「{name}」({x},{y}) 置信:{conf:.2f}")
        self._update_tray_tooltip(f"已点击 {self.click_count} 次")
        self.root.after(1500, lambda: (
            self.widget.set_status("监控中...", self.c['success'])
            if self.monitoring else None))

    def _emergency_stop(self):
        self._stop_monitoring()
        messagebox.showwarning("紧急停止", "鼠标移至屏幕左上角，已紧急停止！")

    # ── 配置 ──────────────────────────────────────────
    def save_config(self):
        try:
            cfg = {'interval': self.interval.get(),
                   'confidence': self.confidence.get(),
                   'cooldown': self.cooldown.get()}
            with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
                json.dump(cfg, f, indent=2)
        except Exception:
            pass

    def _load_config(self):
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
                    cfg = json.load(f)
                self.interval.set(cfg.get('interval', DEFAULT_INTERVAL))
                self.confidence.set(cfg.get('confidence', DEFAULT_CONFIDENCE))
                self.cooldown.set(cfg.get('cooldown', DEFAULT_COOLDOWN))
        except Exception:
            pass

    def _load_history(self):
        """启动时从磁盘加载已有的历史截图"""
        try:
            files = sorted(glob.glob(os.path.join(HISTORY_DIR, "*.png")))
            # 只保留最近 MAX_HISTORY 个
            if len(files) > MAX_HISTORY:
                for old in files[:-MAX_HISTORY]:
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                files = files[-MAX_HISTORY:]

            for filepath in files:
                fname = os.path.splitext(os.path.basename(filepath))[0]
                # 文件名格式: 20260317_143005_模板1
                parts = fname.split('_', 2)
                if len(parts) >= 3:
                    ts = parts[1]  # HHMMSS
                    ts_display = f"{ts[:2]}:{ts[2:4]}:{ts[4:6]}" if len(ts) == 6 else ts
                    name = parts[2]
                else:
                    ts_display = "--:--:--"
                    name = fname

                idx = len(self.click_history) + 1
                self.click_history.append((ts_display, filepath, name, idx))
        except Exception:
            pass

    # ── 启动 ──────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ══════════════════════════════════════════════════════
if __name__ == "__main__":
    app = AutoAllowApp()
    app.run()
