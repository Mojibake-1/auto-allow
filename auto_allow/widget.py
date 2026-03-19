"""
浮窗控件（自动展开/折叠）
"""

import math
import tkinter as tk
from PIL import Image, ImageTk, ImageDraw


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
